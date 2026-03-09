import Foundation
import HealthKit

final class HealthKitManager {
    private let healthStore = HKHealthStore()
    private let stepType = HKObjectType.quantityType(forIdentifier: .stepCount)!

    func requestStepReadAuthorization() async throws {
        guard HKHealthStore.isHealthDataAvailable() else {
            throw HealthSyncError.healthDataUnavailable
        }
        try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Void, Error>) in
            healthStore.requestAuthorization(toShare: [], read: [stepType]) { success, error in
                if let error {
                    continuation.resume(throwing: error)
                    return
                }
                if success {
                    continuation.resume()
                } else {
                    continuation.resume(
                        throwing: HealthSyncError.invalidConfig("HealthKit permission was not granted.")
                    )
                }
            }
        }
    }

    func fetchDailySteps(lastNDays days: Int) async throws -> [DailyStepSample] {
        guard HKHealthStore.isHealthDataAvailable() else {
            throw HealthSyncError.healthDataUnavailable
        }
        let boundedDays = max(1, min(days, 365))
        let calendar = Calendar.current
        let now = Date()
        let todayStart = calendar.startOfDay(for: now)
        guard let startDate = calendar.date(byAdding: .day, value: -(boundedDays - 1), to: todayStart),
              let endDateExclusive = calendar.date(byAdding: .day, value: 1, to: todayStart) else {
            throw HealthSyncError.invalidConfig("Unable to build date range for HealthKit query.")
        }

        let predicate = HKQuery.predicateForSamples(
            withStart: startDate,
            end: endDateExclusive,
            options: .strictStartDate
        )
        var interval = DateComponents()
        interval.day = 1
        let anchorDate = calendar.startOfDay(for: startDate)

        return try await withCheckedThrowingContinuation { continuation in
            let query = HKStatisticsCollectionQuery(
                quantityType: stepType,
                quantitySamplePredicate: predicate,
                options: .cumulativeSum,
                anchorDate: anchorDate,
                intervalComponents: interval
            )

            query.initialResultsHandler = { _, collection, error in
                if let error {
                    continuation.resume(throwing: error)
                    return
                }
                guard let collection else {
                    continuation.resume(returning: [])
                    return
                }

                var results: [DailyStepSample] = []
                collection.enumerateStatistics(from: startDate, to: endDateExclusive) { stats, _ in
                    let steps = Int(stats.sumQuantity()?.doubleValue(for: HKUnit.count()) ?? 0)
                    let sampleDate = calendar.startOfDay(for: stats.startDate)
                    let timeZone = TimeZone.current
                    results.append(
                        DailyStepSample(
                            sampleDate: sampleDate,
                            stepCount: steps,
                            startAt: stats.startDate,
                            endAt: stats.endDate,
                            timeZoneIdentifier: timeZone.identifier,
                            sourceName: "Apple Health",
                            sourceBundleId: "com.apple.Health",
                            sourceUUID: nil
                        )
                    )
                }
                continuation.resume(returning: results.sorted { $0.sampleDate < $1.sampleDate })
            }

            healthStore.execute(query)
        }
    }
}
